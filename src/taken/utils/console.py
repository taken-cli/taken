from rich.console import Console

# Primary console — stdout, used for all normal output
console = Console()

# Error console — stderr, used for all error panels and warnings
# Keeping errors on stderr means normal output can be piped cleanly
err_console = Console(stderr=True)
