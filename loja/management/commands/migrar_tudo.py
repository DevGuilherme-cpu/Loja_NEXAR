"""python manage.py migrar_tudo

Aplica as migrations no banco local (MySQL) e no Supabase com um comando só.
O endereço do Supabase fica no .env, na linha SUPABASE_DATABASE_URL (o .env nunca vai para o GitHub).

Cada banco roda num processo separado do "manage.py migrate": o settings escolhe o banco pela
DATABASE_URL, então as migrations com RunPython também gravam no banco certo.
"""
import os
import subprocess
import sys

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Aplica as migrations no banco local e no Supabase (SUPABASE_DATABASE_URL no .env)."

    def bancos(self):
        local = {k: v for k, v in os.environ.items() if k != "DATABASE_URL"}
        lista = [("banco local", local)]
        if supabase := os.getenv("SUPABASE_DATABASE_URL"):
            lista.append(("Supabase", local | {"DATABASE_URL": supabase}))
        return lista

    def handle(self, *args, **opcoes):
        bancos = self.bancos()
        if len(bancos) == 1:
            self.stdout.write(self.style.WARNING(
                "SUPABASE_DATABASE_URL não está no .env: só o banco local vai ser migrado."))
        for nome, ambiente in bancos:
            self.stdout.write(self.style.MIGRATE_HEADING(f"\nMigrando o {nome}"))
            comando = [sys.executable, str(settings.BASE_DIR / "manage.py"), "migrate"]
            if subprocess.run(comando, env=ambiente).returncode:
                raise CommandError(f"O migrate falhou no {nome}. Os bancos seguintes não foram tocados.")
        self.stdout.write(self.style.SUCCESS("\nMigrations em dia em todos os bancos."))
