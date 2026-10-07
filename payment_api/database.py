import os
from dotenv import load_dotenv

load_dotenv()

import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()