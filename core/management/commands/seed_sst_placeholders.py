from datetime import date

from django.core.management.base import BaseCommand

from core.models import Insight, Project, SiteStat

STATS = [
    ("Projects", "0+"),
    ("Partners", "0+"),
    ("People Reached", "0+"),
    ("Our Commitment", "A Greener Tanzania"),
]

PLACEHOLDER_PROJECT = {
    "title": "Sample Project (replace with a real one)",
    "date_range": "2026, Ongoing",
    "summary": (
        "This is a placeholder project entry so the Projects page has something to "
        "show. Edit or delete it from /admin/ and add SST's real projects."
    ),
}

PLACEHOLDER_INSIGHTS = [
    (Insight.CATEGORY_NEWS, "Sample news item (replace with a real one)"),
    (Insight.CATEGORY_PUBLICATION, "Sample publication (replace with a real one)"),
    (Insight.CATEGORY_EVENT, "Sample event (replace with a real one)"),
    (Insight.CATEGORY_CAREER, "Sample career opportunity (replace with a real one)"),
    (Insight.CATEGORY_STARTUP, "Sample startup competition (replace with a real one)"),
    (Insight.CATEGORY_CONFERENCE, "Sample conference (replace with a real one)"),
]


class Command(BaseCommand):
    help = "Seed placeholder SiteStat/Project/Insight rows for the SST site sections."

    def handle(self, *args, **options):
        stat_count = 0
        for label, value in STATS:
            _, created = SiteStat.objects.get_or_create(label=label, defaults={"value": value})
            if created:
                stat_count += 1
        self.stdout.write(f"Created {stat_count} new site stats.")

        if not Project.objects.filter(title=PLACEHOLDER_PROJECT["title"]).exists():
            Project.objects.create(
                title=PLACEHOLDER_PROJECT["title"],
                date_range=PLACEHOLDER_PROJECT["date_range"],
                summary=PLACEHOLDER_PROJECT["summary"],
            )
            self.stdout.write("Created 1 placeholder project.")
        else:
            self.stdout.write("Placeholder project already exists.")

        insight_count = 0
        for category, title in PLACEHOLDER_INSIGHTS:
            if not Insight.objects.filter(title=title).exists():
                Insight.objects.create(
                    category=category,
                    title=title,
                    summary="Placeholder entry: edit or delete this from /admin/.",
                    published_at=date.today(),
                )
                insight_count += 1
        self.stdout.write(f"Created {insight_count} new placeholder insights.")

        self.stdout.write(self.style.SUCCESS("Placeholder seed complete."))
