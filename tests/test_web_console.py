import ast
import io
import unittest
from contextlib import redirect_stdout

import app
import run_all
import web_console


class GeneratedPythonSanitizerTests(unittest.TestCase):
    def test_extracts_python_from_fenced_response_with_prose(self):
        response = (
            'Here is the requested test:\n'
            '``` py\n'
            'import unittest\n\n'
            'class TestExample(unittest.TestCase):\n'
            '    pass\n'
            '```\n'
            'This covers the requested steps.'
        )

        code = web_console._sanitize_generated_python(response)

        self.assertEqual(
            'import unittest\n\nclass TestExample(unittest.TestCase):\n    pass',
            code,
        )
        ast.parse(code)

    def test_rejects_response_without_python_source(self):
        self.assertEqual('', web_console._sanitize_generated_python('I cannot generate that script.'))

    def test_keeps_code_when_no_line_matches_start_marker_exactly(self):
        # A stray leading BOM can prevent the line-start regex from matching on
        # every line even though the response is real, unfenced Python source.
        response = '\ufeffclass TestExample(unittest.TestCase):\n    pass'

        code = web_console._sanitize_generated_python(response)

        self.assertIn('class TestExample(unittest.TestCase):', code)
        self.assertIn('pass', code)


class SkippedRunStateTests(unittest.TestCase):
    def test_normalize_task_record_preserves_skipped_count(self):
        task = app.normalize_task_record({'lastRunSkipped': 3})

        self.assertEqual(3, task['lastRunSkipped'])


class _BeautifulReportStyleResult(unittest.TestResult):
    def __init__(self):
        super().__init__()
        self.failure_count = 0
        self.skipped = 0

    def addFailure(self, test, err):
        self.failure_count += 1

    def addSkip(self, test, reason):
        self.skipped += 1


class ProgressOutcomeTests(unittest.TestCase):
    def test_beautiful_report_failure_emits_fail_progress(self):
        class FailingCase(unittest.TestCase):
            def test_failure(self):
                self.fail('expected failure')

        wrapped = run_all._ProgressWrappedCase(FailingCase('test_failure'), 1, 1)
        output = io.StringIO()
        with redirect_stdout(output):
            wrapped.run(_BeautifulReportStyleResult())

        self.assertIn('[AUTONEXUS_PROGRESS] END 1/1 FAIL', output.getvalue())

    def test_beautiful_report_skip_emits_skip_progress(self):
        class SkippedCase(unittest.TestCase):
            @unittest.skip('not applicable')
            def test_skip(self):
                pass

        wrapped = run_all._ProgressWrappedCase(SkippedCase('test_skip'), 1, 1)
        output = io.StringIO()
        with redirect_stdout(output):
            wrapped.run(_BeautifulReportStyleResult())

        self.assertIn('[AUTONEXUS_PROGRESS] END 1/1 SKIP', output.getvalue())


if __name__ == '__main__':
    unittest.main()
