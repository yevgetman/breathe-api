"""
Management command to create, list, and revoke API keys.

Usage:
    python manage.py manage_api_keys create --name "JASPR iOS App"
    python manage.py manage_api_keys list
    python manage.py manage_api_keys revoke --key abc123...
"""
from django.core.management.base import BaseCommand

from apps.core.models import APIKey


class Command(BaseCommand):
    help = 'Create, list, or revoke API keys'

    def add_arguments(self, parser):
        subparsers = parser.add_subparsers(dest='action', help='Action to perform')

        create_parser = subparsers.add_parser('create', help='Create a new API key')
        create_parser.add_argument('--name', required=True, help='Label for the key')

        subparsers.add_parser('list', help='List all API keys')

        revoke_parser = subparsers.add_parser('revoke', help='Revoke an API key')
        revoke_parser.add_argument('--key', required=True, help='The key to revoke (full or prefix)')

    def handle(self, *args, **options):
        action = options.get('action')

        if action == 'create':
            self._create(options['name'])
        elif action == 'list':
            self._list()
        elif action == 'revoke':
            self._revoke(options['key'])
        else:
            self.stderr.write('Usage: manage_api_keys {create|list|revoke}')

    def _create(self, name):
        api_key = APIKey.generate(name=name)
        self.stdout.write(self.style.SUCCESS(f'API key created:'))
        self.stdout.write(f'  Name: {name}')
        self.stdout.write(f'  Key:  {api_key.key}')
        self.stdout.write('')
        self.stdout.write('Store this key securely — it will not be shown again in full.')

    def _list(self):
        keys = APIKey.objects.all()
        if not keys.exists():
            self.stdout.write('No API keys found.')
            return

        self.stdout.write(f'{"Name":<30} {"Key Prefix":<15} {"Active":<8} {"Created"}')
        self.stdout.write('-' * 80)
        for k in keys:
            self.stdout.write(
                f'{k.name:<30} {k.key[:12]}...  {"Yes" if k.is_active else "No":<8} {k.created_at.strftime("%Y-%m-%d %H:%M")}'
            )

    def _revoke(self, key_input):
        try:
            api_key = APIKey.objects.get(key__startswith=key_input, is_active=True)
        except APIKey.DoesNotExist:
            self.stderr.write(self.style.ERROR(f'No active key found matching "{key_input}"'))
            return
        except APIKey.MultipleObjectsReturned:
            self.stderr.write(self.style.ERROR(f'Multiple keys match "{key_input}" — provide more characters'))
            return

        api_key.is_active = False
        api_key.save()
        self.stdout.write(self.style.SUCCESS(f'Revoked key: {api_key.name} ({api_key.key[:12]}...)'))
