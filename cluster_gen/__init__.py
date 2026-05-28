"""Package de génération des fichiers docker-compose pour le cluster ES."""

from .constants import ES_IMAGE, KIBANA_IMAGE, NOEUDS_PRINCIPAUX, MIN_NOEUDS

__all__ = ["ES_IMAGE", "KIBANA_IMAGE", "NOEUDS_PRINCIPAUX", "MIN_NOEUDS"]
