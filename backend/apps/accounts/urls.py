from django.urls import path

from apps.accounts.views import DevLoginView, EmailLoginView, EmailRegisterView, GoogleLoginView

urlpatterns = [
    path("google/", GoogleLoginView.as_view(), name="google-login"),
    path("register/", EmailRegisterView.as_view(), name="email-register"),
    path("email-login/", EmailLoginView.as_view(), name="email-login"),
    # DEV LOGIN BACKDOOR — REMOVE WHEN GOOGLE OAUTH IS FULLY WORKING
    path("dev-login/", DevLoginView.as_view(), name="dev-login"),
]
