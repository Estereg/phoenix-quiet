import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import patch_phoenix

KEY = b"0123456789abcdef" * 2
DSN = b"https://" + KEY + b"@o12345.ingest.us.sentry.io/6789012345"
CREDENTIAL = (
    b'"credential":"k2026a:'
    + b"ab" * 20
    + b':Zm9vYmFyLWJheg","endpoint":"https://x.example/v1/batch"'
)
HOSTS = b"".join(
    b"https://" + h + b".vibeyard.tools"
    for h in (
        b"phoenix-errmon",
        b"phoenix-external-reports",
        b"project-phoenix",
        b"phoenix-external-reports",
    )
)
SOURCE_PATH = b"crates/http/src/routes/science.rs"
BLOB = b"\x7fELF\0\0" + b"\0".join(
    [
        DSN,
        CREDENTIAL,
        HOSTS,
        SOURCE_PATH,
        b"drive/science",
        b"img.litix.io",
        b"https://api.lab.amplitude.com",
        b"discord.com/api/v9",
    ]
)


def run(*argv):
    return patch_phoenix.main(list(argv))


class PatchTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.src = os.path.join(self.tmp.name, "phoenix")
        self.out = os.path.join(self.tmp.name, "phoenix.patched")
        with open(self.src, "wb") as f:
            f.write(BLOB)
        os.chmod(self.src, 0o755)

    def patched(self) -> bytes:
        with open(self.out, "rb") as f:
            return f.read()

    def test_patch_clears_every_signature(self):
        self.assertEqual(run("check", self.src), 1)
        self.assertEqual(run("patch", self.src, "-o", self.out), 0)
        self.assertEqual(run("check", self.out), 0)

    def test_layout_is_preserved(self):
        run("patch", self.src, "-o", self.out)
        self.assertEqual(len(self.patched()), len(BLOB))
        self.assertTrue(os.access(self.out, os.X_OK))

    def test_input_is_untouched(self):
        run("patch", self.src, "-o", self.out)
        with open(self.src, "rb") as f:
            self.assertEqual(f.read(), BLOB)

    def test_unrelated_strings_survive(self):
        run("patch", self.src, "-o", self.out)
        data = self.patched()
        self.assertIn(SOURCE_PATH, data)
        self.assertIn(b"discord.com/api/v9", data)
        self.assertNotIn(b"drive/science", data)

    def test_replacements_never_resolve(self):
        run("patch", self.src, "-o", self.out)
        data = self.patched()
        self.assertIn(b".invalid", data)
        for needle in (KEY, b"sentry.io", b"vibeyard", b"litix", b"amplitude"):
            self.assertNotIn(needle, data)

    def test_other_build_with_different_endpoints(self):
        other = b"\0".join(
            [
                b"https://" + b"f" * 32 + b"@o1.ingest.eu.sentry.io/42",
                b"https://reports.vibeyard.tools/v2/batch",
                b"/science",
            ]
        )
        with open(self.src, "wb") as f:
            f.write(other)
        self.assertEqual(run("patch", self.src, "-o", self.out), 0)
        self.assertEqual(run("check", self.out), 0)
        self.assertEqual(len(self.patched()), len(other))

    def test_non_phoenix_binary_writes_nothing(self):
        with open(self.src, "wb") as f:
            f.write(BLOB.replace(KEY, b"z" * 32))
        self.assertEqual(run("patch", self.src, "-o", self.out), 1)
        self.assertFalse(os.path.exists(self.out))

    def test_refuses_to_overwrite_input(self):
        self.assertEqual(run("patch", self.src, "-o", self.src), 2)
        with open(self.src, "rb") as f:
            self.assertEqual(f.read(), BLOB)

    def test_patching_twice_fails_loudly(self):
        run("patch", self.src, "-o", self.out)
        again = self.out + ".2"
        self.assertEqual(run("patch", self.out, "-o", again), 1)


if __name__ == "__main__":
    unittest.main()
