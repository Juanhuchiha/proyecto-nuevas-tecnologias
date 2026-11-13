import getpass
import os

from backend.config import load_environment
from backend.database.persistence import SQLiteStore


def main():
    load_environment()
    environment = os.getenv("MESA_ROJA_ENV", "").strip().lower()
    demo_mode = os.getenv("MESA_ROJA_DEMO_MODE", "").strip().lower()
    if environment not in {"development", "demo"} or demo_mode not in {
        "1",
        "true",
        "yes",
    }:
        raise SystemExit(
            "La preparación de cuentas demo requiere MESA_ROJA_ENV=development "
            "o demo y MESA_ROJA_DEMO_MODE=true."
        )

    password = getpass.getpass("Contraseña para las cuentas demo (no se mostrará): ")
    confirmation = getpass.getpass("Confirma la contraseña demo: ")
    if password != confirmation:
        raise SystemExit("Las contraseñas no coinciden.")
    if len(password) < 6:
        raise SystemExit("La contraseña demo debe tener al menos 6 caracteres.")

    store = SQLiteStore(os.getenv("SQLITE_DATABASE_PATH"))
    store.initialize()
    result = store.seed_demo_users(password)
    print(
        "Preparación completada: "
        f"{result['created']} creadas, "
        f"{result['updated']} actualizadas, "
        f"{result['unchanged']} sin cambios."
    )


if __name__ == "__main__":
    main()
