from django.urls import path

from apps.reviews.views import create_message, list_reviews, my_review

urlpatterns = [
    path("", list_reviews, name="reviews-list"),
    path("mine/", my_review, name="reviews-mine"),
    path("<int:review_id>/messages/", create_message, name="reviews-create-message"),
]
