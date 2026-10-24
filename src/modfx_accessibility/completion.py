"""Shell completion scripts for bash, zsh and fish.

The scripts are generated from the same command table the CLI uses, so a new subcommand
only has to be registered once. They are printed to stdout; the documentation shows how
to install them for each shell.
"""

from __future__ import annotations

PROGRAM = "modfx-a11y"

#: Subcommands with their long options. Keep in sync with :mod:`modfx_accessibility.cli`.
COMMANDS: dict[str, tuple[str, ...]] = {
    "lint": ("--format", "--strict", "--fail-on", "--min-severity", "--fix", "--baseline",
             "--baseline-write", "--config", "--no-config", "--exclude", "--output", "--quiet"),
    "init": ("--mod-id", "--template", "--category"),
    "fmt": ("--check", "--sort-effects", "--quiet"),
    "stats": ("--format", "--output", "--config", "--no-config", "--exclude"),
    "diff": ("--format", "--output"),
    "pack": ("--format", "--strict", "--fail-on", "--min-severity", "--config", "--no-config",
             "--exclude", "--output"),
    "rules": ("--format", "--group"),
    "explain": ("--format",),
    "schema": ("--output",),
    "completion": (),
    "doctor": ("--json", "--config", "--no-config"),
}

SHELLS: tuple[str, ...] = ("bash", "zsh", "fish")

_VALUE_OPTIONS = {
    "--format", "--fail-on", "--min-severity", "--baseline", "--baseline-write", "--config",
    "--exclude", "--output", "--mod-id", "--template", "--category", "--group",
}


def bash_script(program: str = PROGRAM) -> str:
    """Build a bash completion script.

    Args:
        program: Executable name to complete.

    Returns:
        str: Script text ending with a newline.
    """
    names = " ".join(COMMANDS)
    cases = []
    for command, options in COMMANDS.items():
        option_words = " ".join(options)
        cases.append(f'        {command}) opts="{option_words}" ;;')
    return f"""# bash completion for {program}
# Install: {program} completion bash > /etc/bash_completion.d/{program}
_{program.replace('-', '_')}_complete() {{
    local cur prev commands opts
    cur="${{COMP_WORDS[COMP_CWORD]}}"
    prev="${{COMP_WORDS[COMP_CWORD-1]}}"
    commands="{names}"
    opts=""
    if [ "$COMP_CWORD" -eq 1 ]; then
        COMPREPLY=( $(compgen -W "$commands --version --help" -- "$cur") )
        return 0
    fi
    case "${{COMP_WORDS[1]}}" in
{chr(10).join(cases)}
    esac
    case "$prev" in
        --format) COMPREPLY=( $(compgen -W "text json markdown sarif junit html csv github" -- "$cur") ); return 0 ;;
        --fail-on) COMPREPLY=( $(compgen -W "none error warning" -- "$cur") ); return 0 ;;
        --min-severity) COMPREPLY=( $(compgen -W "warning error" -- "$cur") ); return 0 ;;
        --template) COMPREPLY=( $(compgen -W "minimal full" -- "$cur") ); return 0 ;;
    esac
    COMPREPLY=( $(compgen -W "$opts" -- "$cur") $(compgen -f -- "$cur") )
    return 0
}}
complete -F _{program.replace('-', '_')}_complete {program}
"""


def zsh_script(program: str = PROGRAM) -> str:
    """Build a zsh completion script.

    Args:
        program: Executable name to complete.

    Returns:
        str: Script text ending with a newline.
    """
    command_lines = "\n".join(
        f"        '{command}:{command} manifests'" for command in COMMANDS
    )
    option_lines = "\n".join(
        f"                '({option})'{{--{option.lstrip('-')}}}'[option]'"
        for option in sorted({opt for options in COMMANDS.values() for opt in options})
    )
    return f"""#compdef {program}
# zsh completion for {program}
# Install: {program} completion zsh > "${{fpath[1]}}/_{program}"
_{program.replace('-', '_')}() {{
    local -a commands
    commands=(
{command_lines}
    )
    _arguments -C \\
        '1:command:->command' \\
        '*::arg:->args'
    case $state in
        command)
            _describe 'command' commands
            ;;
        args)
            case $words[2] in
                lint|pack)
                    _arguments \\
{option_lines}
                    ;;
            esac
            ;;
    esac
}}
_{program.replace('-', '_')} "$@"
"""


def fish_script(program: str = PROGRAM) -> str:
    """Build a fish completion script.

    Args:
        program: Executable name to complete.

    Returns:
        str: Script text ending with a newline.
    """
    lines = [
        f"# fish completion for {program}",
        f"# Install: {program} completion fish > ~/.config/fish/completions/{program}.fish",
        f"complete -c {program} -f",
    ]
    for command in COMMANDS:
        lines.append(f"complete -c {program} -n '__fish_use_subcommand' -a '{command}'")
    for command, options in COMMANDS.items():
        for option in options:
            name = option.lstrip("-")
            if option in _VALUE_OPTIONS:
                lines.append(f"complete -c {program} -n '__fish_seen_subcommand_from {command}' -l {name} -r")
            else:
                lines.append(f"complete -c {program} -n '__fish_seen_subcommand_from {command}' -l {name}")
    lines.append(f"complete -c {program} -n '__fish_seen_subcommand_from completion' -a 'bash zsh fish'")
    lines.append(
        f"complete -c {program} -n '__fish_seen_subcommand_from lint pack' -l format -a 'text json markdown sarif junit html csv github'"
    )
    lines.append(f"complete -c {program} -n '__fish_seen_subcommand_from lint pack' -l fail-on -a 'none error warning'")
    return "\n".join(lines) + "\n"


def script(shell: str, program: str = PROGRAM) -> str:
    """Return the completion script for a shell.

    Args:
        shell: One of :data:`SHELLS`.
        program: Executable name to complete.

    Returns:
        str: Script text.

    Raises:
        ValueError: If the shell is not supported.
    """
    builders = {"bash": bash_script, "zsh": zsh_script, "fish": fish_script}
    if shell not in builders:
        raise ValueError(f"Unsupported shell '{shell}'. Choose one of: {', '.join(SHELLS)}.")
    return builders[shell](program)
