"""Public user surfaces.

GET /u/{display_name} renders an author's profile with their published
posts in reverse-chronological order. Reachable anonymously — no
``current_user`` dependency. Lookup is case-insensitive but the URL is
canonicalized to the stored case via a 302 redirect.
"""
