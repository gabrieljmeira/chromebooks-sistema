"""Gera hash da senha da TI sem armazenar a senha em arquivo."""
from getpass import getpass
from werkzeug.security import generate_password_hash

password = getpass('Crie uma senha forte para a TI: ')
if len(password) < 12:
    raise SystemExit('Use uma senha com pelo menos 12 caracteres.')
print('Cole esta linha no .env (sem aspas):')
print('ADMIN_PASSWORD_HASH=' + generate_password_hash(password))
