import sys

from sprouted_build.commands import CommandRunner


def test_dry_run_records_without_executing() -> None:
    runner = CommandRunner(dry_run=True)

    result = runner.run(["definitely-not-a-real-command", "argument"])

    assert result is None
    assert runner.commands == [("definitely-not-a-real-command", "argument")]


def test_runner_executes_argument_list_without_a_shell() -> None:
    runner = CommandRunner()

    result = runner.run(
        [sys.executable, "-c", "print('sprouted')"],
        capture_output=True,
    )

    assert result is not None
    assert result.stdout.strip() == "sprouted"


def test_runner_can_send_text_to_standard_input() -> None:
    runner = CommandRunner()

    result = runner.run(
        [sys.executable, "-c", "import sys; print(sys.stdin.read().upper())"],
        input_text="sprouted",
        capture_output=True,
    )

    assert result is not None
    assert result.stdout.strip() == "SPROUTED"
