import asyncio

from django.core.management.base import BaseCommand

from dashboard.orchestrator.adapter import InstagramOrchestratorAdapter


class Command(BaseCommand):
    help = "Runs the persistent Instagram adapter connected to the RPA Orchestrator."

    def handle(self, *args, **options):
        adapter = InstagramOrchestratorAdapter()
        try:
            asyncio.run(adapter.run_forever())
        except KeyboardInterrupt:
            self.stdout.write(self.style.WARNING("Instagram orchestrator adapter stopped"))
