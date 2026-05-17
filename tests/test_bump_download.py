import unittest

import bump_download


class TestBumpDownload(unittest.TestCase):
    def test_patch_version_to_tag_removes_dots(self) -> None:
        self.assertEqual("14161", bump_download.patch_version_to_tag("1.41.6.1"))


if __name__ == "__main__":
    unittest.main()
