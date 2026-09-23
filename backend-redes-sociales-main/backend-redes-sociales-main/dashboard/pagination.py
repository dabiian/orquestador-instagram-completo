from rest_framework.pagination import CursorPagination, PageNumberPagination
from rest_framework.response import Response


class PendingBotPagination(CursorPagination):
    page_size = 10
    page_size_query_param = "page_size"
    max_page_size = 100
    ordering = ("start_date", "id")

    def get_paginated_response(self, data):
        links = []
        next_link = self.get_next_link()
        previous_link = self.get_previous_link()

        if next_link:
            links.append(f'<{next_link}>; rel="next"')
        if previous_link:
            links.append(f'<{previous_link}>; rel="prev"')

        headers = {"X-Result-Count": str(len(data))}
        if links:
            headers["Link"] = ", ".join(links)

        return Response(data, headers=headers)


class SocialMediaMessagePagination(PageNumberPagination):
    page_size = 100
    page_size_query_param = "page_size"
    max_page_size = 100
