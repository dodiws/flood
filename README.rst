=====
geodb
=====

Process base mapping data used by other modules.
Mandatory Module for ASDC

Quick start
-----------

1. Add "geodb" to your INSTALLED_APPS setting like this::

    INSTALLED_APPS = [
        ...
        'geodb',
    ]

    If necessary add "geodb" in (check comment for description): 
        DASHBOARD_PAGE_MODULES, 
        GETRISKEXECUTEEXTERNAL_MODULES, 
        QUICKOVERVIEW_MODULES, 
        MAP_APPS_TO_DB_CUSTOM

    For development in virtualenv add GEODB_PARENT_DIR path to VENV_NAME/bin/activate:
        export PYTHONPATH=${PYTHONPATH}:\
        ${HOME}/GEODB_PARENT_DIR

2. Include the geodb URLconf in geonode/urls.py like this::

    url('', include('geodb.urls')),

3. Run `python manage.py migrate geodb` to create the geodb models.

