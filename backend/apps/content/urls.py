from django.urls import path

from apps.content.views import features_list, releases_list, team_list

urlpatterns = [
    path("features/", features_list, name="content-features"),
    path("team/", team_list, name="content-team"),
    path("releases/", releases_list, name="content-releases"),
]
