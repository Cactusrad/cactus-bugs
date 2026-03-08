"""
HTTP client for the bugs_service API.

Provides a BugsClient class for interacting with the bugs tracking
service (issues, comments, attachments, stats).

Usage:
    from app.services.bugs_client import get_bugs_client

    client = get_bugs_client()
    issues, error = client.list_issues(status='open')
    if error:
        print(f"Error: {error}")
    else:
        print(issues)
"""

import requests


class BugsClient:
    """HTTP client for the bugs_service REST API."""

    def __init__(self, base_url, api_key):
        """
        Initialize the BugsClient.

        Args:
            base_url: Base URL of the bugs_service (e.g. http://localhost:9010)
            api_key: API key for Bearer token authentication
        """
        self.base_url = base_url.rstrip('/')
        self.api_key = api_key

    def _request(self, method, path, **kwargs):
        """
        Internal helper to make authenticated HTTP requests.

        Args:
            method: HTTP method (GET, POST, PUT, PATCH, DELETE)
            path: API path (e.g. /api/v1/issues)
            **kwargs: Additional arguments passed to requests.request()

        Returns:
            tuple: (response_json, None) on success, or (None, error_string) on failure
        """
        url = f"{self.base_url}{path}"

        headers = kwargs.pop('headers', {})
        headers['Authorization'] = f"Bearer {self.api_key}"

        timeout = kwargs.pop('timeout', 10)

        try:
            response = requests.request(
                method,
                url,
                headers=headers,
                timeout=timeout,
                **kwargs
            )
            response.raise_for_status()

            # Some endpoints may return empty body (204 No Content)
            if response.status_code == 204 or not response.content:
                return ({}, None)

            return (response.json(), None)

        except requests.exceptions.Timeout:
            return (None, f"Timeout lors de la requete vers {url}")
        except requests.exceptions.ConnectionError:
            return (None, f"Impossible de se connecter a {url}")
        except requests.exceptions.HTTPError as e:
            # Try to extract error detail from response body
            error_detail = ''
            try:
                body = e.response.json()
                error_detail = body.get('error', body.get('message', body.get('detail', '')))
            except (ValueError, AttributeError):
                error_detail = e.response.text[:200] if e.response is not None else ''
            status_code = e.response.status_code if e.response is not None else 'unknown'
            return (None, f"HTTP {status_code}: {error_detail}" if error_detail else f"HTTP {status_code}")
        except Exception as e:
            return (None, f"Erreur inattendue: {str(e)}")

    def _raw_request(self, method, path, **kwargs):
        """
        Internal helper for requests that return raw content (file downloads).

        Args:
            method: HTTP method
            path: API path
            **kwargs: Additional arguments passed to requests.request()

        Returns:
            tuple: (response, None) on success, or (None, error_string) on failure.
                   The response object has stream=True for efficient proxying.
        """
        url = f"{self.base_url}{path}"

        headers = kwargs.pop('headers', {})
        headers['Authorization'] = f"Bearer {self.api_key}"

        timeout = kwargs.pop('timeout', 30)

        try:
            response = requests.request(
                method,
                url,
                headers=headers,
                timeout=timeout,
                stream=True,
                **kwargs
            )
            response.raise_for_status()
            return (response, None)

        except requests.exceptions.Timeout:
            return (None, f"Timeout lors du telechargement depuis {url}")
        except requests.exceptions.ConnectionError:
            return (None, f"Impossible de se connecter a {url}")
        except requests.exceptions.HTTPError as e:
            status_code = e.response.status_code if e.response is not None else 'unknown'
            return (None, f"HTTP {status_code}")
        except Exception as e:
            return (None, f"Erreur inattendue: {str(e)}")

    # -------------------------------------------------------------------------
    # Issues
    # -------------------------------------------------------------------------

    def list_issues(self, page=1, limit=20, status=None, type=None,
                    priority=None, assignee=None):
        """
        List issues with optional filters.

        Args:
            page: Page number (default 1)
            limit: Items per page (default 20)
            status: Filter by status (open, in_progress, resolved, closed)
            type: Filter by type (bug, feature, task)
            priority: Filter by priority (low, medium, high, critical)
            assignee: Filter by assignee

        Returns:
            tuple: (data_dict, None) on success, or (None, error_string) on failure
        """
        params = {'page': page, 'limit': limit}
        if status:
            params['status'] = status
        if type:
            params['type'] = type
        if priority:
            params['priority'] = priority
        if assignee:
            params['assignee'] = assignee

        return self._request('GET', '/api/v1/issues', params=params)

    def get_issue(self, reference):
        """
        Get issue detail including comments, attachments, and history.

        Args:
            reference: Issue reference (e.g. BUG-0001)

        Returns:
            tuple: (issue_dict, None) on success, or (None, error_string) on failure
        """
        return self._request('GET', f'/api/v1/issues/{reference}')

    def create_issue(self, data):
        """
        Create a new issue.

        Args:
            data: Dict with issue fields:
                - type (str): bug, feature, task
                - title (str): Issue title
                - description (str): Detailed description
                - priority (str): low, medium, high, critical
                - reporter (str): Reporter name
                - assignee (str, optional): Assignee name
                - tags (list, optional): List of tags

        Returns:
            tuple: (created_issue_dict, None) on success, or (None, error_string) on failure
        """
        return self._request('POST', '/api/v1/issues', json=data)

    def update_issue(self, reference, data):
        """
        Update an existing issue.

        Args:
            reference: Issue reference (e.g. BUG-0001)
            data: Dict with fields to update (title, description, priority, assignee, etc.)

        Returns:
            tuple: (updated_issue_dict, None) on success, or (None, error_string) on failure
        """
        return self._request('PUT', f'/api/v1/issues/{reference}', json=data)

    def update_status(self, reference, status, assignee=None, comment=None):
        """
        Update issue status (with optional assignee and comment).

        Args:
            reference: Issue reference (e.g. BUG-0001)
            status: New status (open, in_progress, resolved, closed)
            assignee: Optional new assignee
            comment: Optional status change comment

        Returns:
            tuple: (result_dict, None) on success, or (None, error_string) on failure
        """
        data = {'status': status}
        if assignee is not None:
            data['assignee'] = assignee
        if comment is not None:
            data['comment'] = comment

        return self._request('PATCH', f'/api/v1/issues/{reference}/status', json=data)

    # -------------------------------------------------------------------------
    # Comments
    # -------------------------------------------------------------------------

    def add_comment(self, reference, author, content):
        """
        Add a comment to an issue.

        Args:
            reference: Issue reference (e.g. BUG-0001)
            author: Comment author name
            content: Comment text

        Returns:
            tuple: (comment_dict, None) on success, or (None, error_string) on failure
        """
        data = {'author': author, 'content': content}
        return self._request('POST', f'/api/v1/issues/{reference}/comments', json=data)

    # -------------------------------------------------------------------------
    # Attachments
    # -------------------------------------------------------------------------

    def upload_attachment(self, reference, file_storage):
        """
        Upload an attachment to an issue.

        Args:
            reference: Issue reference (e.g. BUG-0001)
            file_storage: Flask FileStorage object (from request.files)

        Returns:
            tuple: (attachment_dict, None) on success, or (None, error_string) on failure
        """
        files = {
            'file': (file_storage.filename, file_storage.stream,
                     file_storage.content_type or 'application/octet-stream')
        }
        return self._request('POST', f'/api/v1/issues/{reference}/attachments',
                             files=files)

    def download_attachment(self, attachment_id):
        """
        Download an attachment by ID (raw response for proxying).

        Args:
            attachment_id: Attachment ID

        Returns:
            tuple: (response, None) on success, or (None, error_string) on failure.
                   The response object is streamed. Access headers via
                   response.headers for content-type, content-disposition, etc.
        """
        return self._raw_request('GET', f'/api/v1/attachments/{attachment_id}')

    def download_thumbnail(self, attachment_id):
        """
        Download an attachment thumbnail by ID (raw response for proxying).

        Args:
            attachment_id: Attachment ID

        Returns:
            tuple: (response, None) on success, or (None, error_string) on failure.
                   The response object is streamed. Access headers via
                   response.headers for content-type, etc.
        """
        return self._raw_request('GET', f'/api/v1/attachments/{attachment_id}/thumbnail')

    # -------------------------------------------------------------------------
    # Stats
    # -------------------------------------------------------------------------

    def get_stats(self):
        """
        Get bugs_service statistics (counts by status, priority, etc.).

        Returns:
            tuple: (stats_dict, None) on success, or (None, error_string) on failure
        """
        return self._request('GET', '/api/v1/stats')


def get_bugs_client():
    """
    Get BugsClient instance from Flask app config.

    Reads BUGS_SERVICE_URL and BUGS_SERVICE_API_KEY from the current
    Flask app configuration.

    Returns:
        BugsClient: Configured client instance
    """
    from flask import current_app
    url = current_app.config.get('BUGS_SERVICE_URL', 'http://localhost:9010')
    key = current_app.config.get('BUGS_SERVICE_API_KEY', '')
    return BugsClient(url, key)
