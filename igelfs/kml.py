"""Data models for key configuration."""

import base64
import io
import json
from dataclasses import dataclass

from igelfs.constants import ExtentType
from igelfs.crypto import CryptoHelper
from igelfs.filesystem import Filesystem
from igelfs.models import ExtentFilesystem, Section


class KmlConfig(dict):
    """Dictionary subclass for handling KML configuration."""

    FILENAME = "kmlconfig.json"

    def get_master_key(self, extent_key: bytes, slot: int = 0) -> bytes:
        """Return master key for key decryption for slot."""
        return CryptoHelper.get_master_key(
            extent_key=extent_key,
            salt=base64.b64decode(self["system"]["salt"]),
            pub=base64.b64decode(self["slots"][slot]["pub"]),
            priv=base64.b64decode(self["slots"][slot]["priv"]),
            level=self["system"]["level"],
        )

    def get_key(
        self,
        name: str | int,  # name may be partition minor
        master_key: bytes,
    ) -> bytes:
        """Return key for name from config."""
        key = base64.b64decode(self["keys"][str(name)])
        return CryptoHelper.aes_xts_decrypt(key, master_key)

    def get_keys(self, master_key: bytes) -> dict[str, bytes]:
        """Return dictionary of all keys."""
        return {name: self.get_key(name, master_key) for name in self["keys"].keys()}

    @classmethod
    def from_bytes(cls: type["KmlConfig"], data: bytes) -> "KmlConfig":
        """Return KmlConfig instance from JSON data as bytes."""
        with io.BytesIO(data) as file:
            return KmlConfig(json.load(file))


@dataclass
class Keyring:
    """Dataclass to handle keys and methods."""

    extent_key: bytes
    master_key: bytes
    kml_config: KmlConfig

    def get_key(self, name: str | int) -> bytes:
        """Return key for name."""
        return self.kml_config.get_key(name, self.master_key)

    def get_keys(self) -> dict[str, bytes]:
        """Return dictionary of all keys."""
        return self.kml_config.get_keys(self.master_key)

    @staticmethod
    def _find_kml_config_in_filesystem(
        filesystem: Filesystem, extent_key: bytes
    ) -> KmlConfig | None:
        """Return first KmlConfig instance found in filesystem."""
        partition_minors = tuple(filesystem.partition_minors_by_directory)
        # Encrypted filesystems are near end of image
        for partition_minor in reversed(partition_minors):
            sections = filesystem.find_sections_by_directory(partition_minor)
            if not (partition := sections[0].partition):
                continue
            for extent in partition.extents:
                if extent.get_type() != ExtentType.WRITEABLE:
                    continue
                payload = Section.get_extent_of(sections, extent)
                for model in ExtentFilesystem.from_bytes_to_generator(payload):
                    try:
                        data = model.decrypt(extent_key)
                        data = ExtentFilesystem.decompress(data)
                        data = ExtentFilesystem.extract_file(data, KmlConfig.FILENAME)
                        return KmlConfig.from_bytes(data)
                    except ImportError as error:
                        # Required dependencies not installed
                        raise error from None
                    except Exception:
                        pass
        return None

    @classmethod
    def from_filesystem(cls: type["Keyring"], filesystem: Filesystem) -> "Keyring":
        """Return keyring from filesystem."""
        boot_id = filesystem.boot_registry.get_boot_id()
        extent_key = CryptoHelper.get_extent_key(boot_id)
        kml_config = cls._find_kml_config_in_filesystem(filesystem, extent_key)
        if not kml_config:
            raise ValueError("Cannot find key configuration data in filesystem")
        master_key = kml_config.get_master_key(extent_key)
        return cls(extent_key=extent_key, master_key=master_key, kml_config=kml_config)
