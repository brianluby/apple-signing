import io
import os
import pathlib
import subprocess
import tarfile
import tempfile
import textwrap
import unittest

WORKFLOW = pathlib.Path(__file__).parents[1] / ".github/workflows/sign-macos.yml"
SCRIPT = textwrap.dedent(WORKFLOW.read_text().split("python3 - <<'PYTHON'\n", 1)[1].split("          PYTHON", 1)[0])


class ArchiveSafety(unittest.TestCase):
    def run_archive(self, members, binary="app/tool"):
        with tempfile.TemporaryDirectory() as directory:
            work = pathlib.Path(directory)
            (work / "input").mkdir()
            with tarfile.open(work / "input/app.tar.gz", "w:gz") as archive:
                for name, kind in members:
                    member = tarfile.TarInfo(name)
                    member.mode = 0o755
                    if kind == "link":
                        member.type = tarfile.SYMTYPE
                        member.linkname = "/tmp/outside"
                        archive.addfile(member)
                    else:
                        data = b"fixture"
                        member.size = len(data)
                        archive.addfile(member, io.BytesIO(data))
            return subprocess.run(["python3", "-c", SCRIPT],
                env={**os.environ, "WORK": directory, "ARCHIVE_NAME": "app.tar.gz", "BINARY_PATH": binary},
                capture_output=True, text=True).returncode

    def test_regular_package(self):
        self.assertEqual(self.run_archive([("app/tool", "file"), ("app/LICENSE", "file")]), 0)

    def test_traversal(self):
        self.assertNotEqual(self.run_archive([("app/../../outside", "file")]), 0)

    def test_symlink(self):
        self.assertNotEqual(self.run_archive([("app/tool", "link")]), 0)

    def test_absolute_path(self):
        self.assertNotEqual(self.run_archive([("/tmp/outside", "file")]), 0)

    def test_duplicate_member(self):
        self.assertNotEqual(self.run_archive([("app/tool", "file"), ("app/tool", "file")]), 0)

    def test_second_package(self):
        self.assertNotEqual(self.run_archive([("app/tool", "file"), ("other/file", "file")]), 0)

    def test_binary_traversal(self):
        self.assertNotEqual(self.run_archive([("app/tool", "file")], "app/../outside"), 0)
