=====
flood
=====

Process and display flood risk and forecast data.
Optional Module for ISDC

Quick start
-----------

1. Add "flood" to your DASHBOARD_PAGE_MODULES setting like this::

    DASHBOARD_PAGE_MODULES = [
        ...
        'flood',
    ]

    If necessary add "flood" in (check comment for description): 
        QUICKOVERVIEW_MODULES, 
        MAP_APPS_TO_DB_CUSTOM

    For development in virtualenv add FLOOD_PROJECT_DIR path to VENV_NAME/bin/activate:
        export PYTHONPATH=${PYTHONPATH}:\
        ${HOME}/FLOOD_PROJECT_DIR

2. To create the flood tables:

   python manage.py makemigrations
   python manage.py migrate flood

