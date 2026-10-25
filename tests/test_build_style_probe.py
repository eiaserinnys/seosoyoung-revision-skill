import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'scripts' / 'build_style_probe.py'
EXAMPLE_CORPUS = ROOT / 'examples' / 'sample-corpus'
EXAMPLE_DRAFT = ROOT / 'examples' / 'sample-draft.md'


def load_probe_module():
    import importlib.util

    spec = importlib.util.spec_from_file_location('build_style_probe', SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class BuildStyleProbeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.probe = load_probe_module()

    def run_probe(self, *arguments, timeout=10):
        return subprocess.run(
            [sys.executable, str(SCRIPT), *map(str, arguments)],
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )

    def test_register_classifies_plain_polite_styles_and_exception(self):
        cases = {
            '문장은 짧게 쓴다.': 'plain',
            '자료를 확인합니다.': 'polite',
            '내용을 다시 보아요.': 'polite',
            '그렇게 하옵니다.': 'polite',
            '이 뜻을 아시옵니까?': 'polite',
            '잠시 살펴보소서.': 'polite',
            '다음에 다시 말하지요.': 'polite',
            '여기까지는 충분하군요.': 'polite',
            '이 문장을 다시 읽어요.': 'polite',
            '결과가 달라졌네요.': 'polite',
            '그렇지요.': 'polite',
            '정답은 아니다.': 'plain',
            '그 말은 아니다!': 'plain',
            '이유가 아니다?': 'plain',
        }
        for sentence, expected in cases.items():
            with self.subTest(sentence=sentence):
                self.assertEqual(self.probe.register_of(sentence), expected)

    def test_example_corpus_generates_reference_and_draft_files(self):
        with tempfile.TemporaryDirectory() as output_dir:
            result = self.run_probe(
                '--corpus-dir', EXAMPLE_CORPUS,
                '--draft', EXAMPLE_DRAFT,
                '--out-dir', output_dir,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            reference = Path(output_dir) / 'ref_corpus.txt'
            draft = Path(output_dir) / 'draft_sents.txt'
            self.assertTrue(reference.is_file())
            self.assertTrue(draft.is_file())
            self.assertGreaterEqual(len(reference.read_text(encoding='utf-8').splitlines()), 20)
            self.assertGreaterEqual(len(draft.read_text(encoding='utf-8').splitlines()), 10)

    def test_allow_empty_corpus_uses_builtin_reference_without_corpus_argument(self):
        with tempfile.TemporaryDirectory() as output_dir:
            result = self.run_probe(
                '--draft', EXAMPLE_DRAFT,
                '--out-dir', output_dir,
                '--allow-empty-corpus',
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn('코퍼스 모드: 내장 기본 기준선 사용', result.stdout)
            reference = Path(output_dir) / 'ref_corpus.txt'
            draft = Path(output_dir) / 'draft_sents.txt'
            self.assertGreaterEqual(len(reference.read_text(encoding='utf-8').splitlines()), 20)
            self.assertTrue(draft.is_file())

    def test_missing_and_empty_drafts_exit_without_waiting(self):
        with tempfile.TemporaryDirectory() as temporary_dir:
            missing = Path(temporary_dir) / 'missing.md'
            missing_result = self.run_probe('--draft', missing, timeout=5)
            self.assertEqual(missing_result.returncode, 2)

            empty = Path(temporary_dir) / 'empty.md'
            empty.write_text('', encoding='utf-8')
            empty_result = self.run_probe('--draft', empty, timeout=5)
            self.assertEqual(empty_result.returncode, 2)

    def test_python_and_markdown_files_have_no_private_or_forbidden_content(self):
        listing = subprocess.run(
            [
                'git', 'ls-files', '--cached', '--others', '--exclude-standard',
                '--', '*.py', '*.md',
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=True,
        )
        paths = [ROOT / line for line in listing.stdout.splitlines() if line]
        em_dash = chr(0x2014)
        long_hyphen = chr(0x2015)
        middle_dot = chr(0x00B7)
        private_path = '/'.join(('', 'home', 'eias'))
        slang_stem = chr(0xBC15)
        slang_endings = ('다', '아', '고', '았', '었', '으면', '면서', '는', '은', '을', '기', '려고')
        slang_pattern = re.compile(re.escape(slang_stem) + '(?:' + '|'.join(slang_endings) + ')')
        violations = []

        for path in paths:
            text = path.read_text(encoding='utf-8')
            for marker, label in (
                (em_dash, 'em dash'),
                (long_hyphen, 'long hyphen'),
                (middle_dot, 'middle dot'),
            ):
                if marker in text:
                    violations.append('%s contains %s' % (path.relative_to(ROOT), label))
            if private_path in text:
                violations.append('%s contains a private path' % path.relative_to(ROOT))
            if slang_pattern.search(text):
                violations.append('%s contains a prohibited slang verb form' % path.relative_to(ROOT))
            if path.suffix.lower() == '.md':
                allowed_frontmatter_lines = set()
                lines = text.splitlines()
                separator = set('-')
                if path.name == 'SKILL.md' and lines and len(lines[0].strip()) >= 3 and set(lines[0].strip()) == separator:
                    for index in range(1, len(lines)):
                        line = lines[index].strip()
                        if len(line) >= 3 and set(line) == separator:
                            allowed_frontmatter_lines.update((0, index))
                            break
                for index, line in enumerate(lines):
                    stripped = line.strip()
                    if len(stripped) >= 3 and set(stripped) == separator and index not in allowed_frontmatter_lines:
                        violations.append(
                            '%s contains a horizontal rule at line %d'
                            % (path.relative_to(ROOT), index + 1)
                        )

        self.assertEqual(violations, [])


if __name__ == '__main__':
    unittest.main()
