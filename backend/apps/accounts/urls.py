from django.urls import path

from apps.accounts.views import DevLoginView, GoogleLoginView

urlpatterns = [
    path("google/", GoogleLoginView.as_view(), name="google-login"),
    # DEV LOGIN BACKDOOR — REMOVE WHEN GOOGLE OAUTH IS FULLY WORKING
    path("dev-login/", DevLoginView.as_view(), name="dev-login"),
]
