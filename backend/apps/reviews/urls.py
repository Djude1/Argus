from django.urls import path

from apps.reviews.views import list_reviews, my_review

urlpatterns = [
    path("", list_reviews, name="reviews-list"),
    path("mine/", my_review, name="reviews-mine"),
]
