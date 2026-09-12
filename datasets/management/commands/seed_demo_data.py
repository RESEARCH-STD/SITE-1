from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.files import File
from django.core.management.base import BaseCommand

from core.models import DataCustodian
from datasets.models import Category, Dataset

SEED_FILES_DIR = settings.BASE_DIR / "seed_files"

CATEGORIES = [
    ("Demographics & Census", "images/categories/demographics-census.jpg"),
    ("Household Budget / Income & Consumption", "images/categories/household-budget.jpg"),
    ("Health & Nutrition", "images/categories/health-nutrition.jpg"),
    ("Education", "images/categories/education.jpg"),
    ("Labour & Employment", "images/categories/labour-employment.jpg"),
    ("Agriculture & Food Security", "images/categories/agriculture-food.jpg"),
    ("Poverty & Living Standards", "images/categories/poverty-living-standards.jpg"),
    ("Gender", "images/categories/gender.jpg"),
    ("Migration & Urbanization", "images/categories/migration-urbanization.jpg"),
]

DATASETS = [
    {
        "title": "Tanzania Population and Housing Census Extract (Mainland Regions)",
        "category": "Demographics & Census",
        "description": "Regional household size, sex ratio, dependency ratio, and literacy indicators across Mainland Tanzania.",
        "region": "Mainland Tanzania, all regions",
        "year": "2022",
        "csv": "tanzania-population-census_SAMPLE.csv",
    },
    {
        "title": "Household Budget Survey (HBS): Consumption Aggregates Sample",
        "category": "Household Budget / Income & Consumption",
        "description": "Household-level food and non-food consumption expenditure aggregates with poverty-line comparisons.",
        "region": "National (Mainland Tanzania, urban & rural)",
        "year": "2017/18",
        "csv": "household-budget-survey-consumption_SAMPLE.csv",
    },
    {
        "title": "Tanzania Demographic and Health Survey (TDHS): Child Nutrition Indicators Sample",
        "category": "Health & Nutrition",
        "description": "Child-level nutrition status indicators (stunting, wasting, underweight) with maternal education context.",
        "region": "National (Mainland & Zanzibar)",
        "year": "2022",
        "csv": "tdhs-child-nutrition_SAMPLE.csv",
    },
    {
        "title": "Basic Education Statistics: School Enrollment and Completion Sample",
        "category": "Education",
        "description": "School-level enrollment, gender parity, pupil-teacher ratio, and completion/dropout indicators.",
        "region": "Mainland Tanzania (regional)",
        "year": "2023",
        "csv": "basic-education-statistics_SAMPLE.csv",
    },
    {
        "title": "Integrated Labour Force Survey (ILFS): Youth Employment Sample",
        "category": "Labour & Employment",
        "description": "Individual-level employment status, sector, informality, and income indicators with a youth focus.",
        "region": "National (Mainland Tanzania)",
        "year": "2020/21",
        "csv": "labour-force-youth-employment_SAMPLE.csv",
    },
    {
        "title": "National Panel Survey (NPS): Smallholder Agriculture Sample (Wave 5)",
        "category": "Agriculture & Food Security",
        "description": "Farm-household level crop, yield, input-use, and food security indicators for smallholder farmers.",
        "region": "Rural Mainland Tanzania",
        "year": "2019/20",
        "csv": "national-panel-survey-agriculture_SAMPLE.csv",
    },
    {
        "title": "Poverty Mapping Dataset: District-Level Poverty Estimates Sample",
        "category": "Poverty & Living Standards",
        "description": "District-level poverty headcount rate, extreme poverty rate, and Gini coefficient estimates.",
        "region": "District-level, Mainland Tanzania",
        "year": "2021",
        "csv": "poverty-mapping-district_SAMPLE.csv",
    },
    {
        "title": "Gender-Based Violence Prevalence Indicators Sample",
        "category": "Gender",
        "description": "Self-reported prevalence of physical/emotional violence and awareness of support services, by age group and region.",
        "region": "National (Mainland Tanzania)",
        "year": "2022",
        "csv": "gender-based-violence-indicators_SAMPLE.csv",
    },
    {
        "title": "Internal Migration and Urbanization Patterns Sample",
        "category": "Migration & Urbanization",
        "description": "Origin-destination migration records with migration reason, years since move, and post-migration employment status.",
        "region": "National (Mainland Tanzania)",
        "year": "2021",
        "csv": "internal-migration-urbanization_SAMPLE.csv",
    },
]

DATA_CUSTODIANS = [
    {
        "name": "National Bureau of Statistics (NBS), Tanzania",
        "url": "https://www.nbs.go.tz/",
        "description": "Tanzania's official statistics agency for census, surveys, and national indicators.",
    },
]


class Command(BaseCommand):
    help = "Seed demo categories, a demo uploader account, sample datasets, and data custodians."

    def handle(self, *args, **options):
        User = get_user_model()

        demo_user, created = User.objects.get_or_create(
            username="demo_uploader",
            defaults={
                "email": "demo@databridge.local",
                "institution": "TakwimuBridge (sample data)",
            },
        )
        if created:
            demo_user.set_unusable_password()
            demo_user.save()
            self.stdout.write("Created demo_uploader account (login disabled).")

        category_map = {}
        for name, icon in CATEGORIES:
            category, _ = Category.objects.get_or_create(name=name, defaults={"icon": icon})
            if category.icon != icon:
                category.icon = icon
                category.save(update_fields=["icon"])
            category_map[name] = category
        self.stdout.write(f"Ensured {len(CATEGORIES)} categories.")

        created_count = 0
        for item in DATASETS:
            if Dataset.objects.filter(title=item["title"]).exists():
                continue
            csv_path = SEED_FILES_DIR / item["csv"]
            if not csv_path.exists():
                self.stderr.write(f"Missing seed file: {csv_path}")
                continue
            dataset = Dataset(
                title=item["title"],
                uploader=demo_user,
                category=category_map[item["category"]],
                description=item["description"],
                region=item["region"],
                year=item["year"],
            )
            dataset.original_filename = item["csv"]
            dataset.file_size = csv_path.stat().st_size
            with open(csv_path, "rb") as f:
                dataset.file.save(item["csv"], File(f), save=False)
            dataset.save()
            created_count += 1
        self.stdout.write(f"Created {created_count} new sample datasets.")

        custodian_count = 0
        for item in DATA_CUSTODIANS:
            _, created = DataCustodian.objects.get_or_create(
                name=item["name"], defaults={"url": item["url"], "description": item["description"]}
            )
            if created:
                custodian_count += 1
        self.stdout.write(f"Created {custodian_count} new data custodians.")

        self.stdout.write(self.style.SUCCESS("Seed complete."))
