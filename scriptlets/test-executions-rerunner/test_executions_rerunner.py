"""
This script will be used by jenkins to rerun test executions as requested
by test observer. Please note that jenkins will download this file then run it.
Therefore, this script can't import from the rest of the codebase and shouldn't be
renamed or moved. Dependencies used by this script must be installed on jenkins.
Note also that jenkins uses python 3.8
"""

from abc import ABC, abstractmethod
from argparse import ArgumentParser
from functools import partial
import logging
from os import environ
import re
from typing import Dict, List, Optional, NamedTuple

from requests import Session
from requests.adapters import HTTPAdapter
from requests.auth import HTTPBasicAuth
from requests.exceptions import HTTPError
from urllib3.util import Retry
from urllib.parse import urlparse

logging.basicConfig(level=logging.INFO)


requests = Session()
retries = Retry(
    total=3,
    backoff_factor=3,
    status_forcelist=[408, 429, 502, 503, 504],
    allowed_methods={"POST", "GET", "DELETE", "PUT"},
)
requests.mount("https://", HTTPAdapter(max_retries=retries))
requests.request = partial(requests.request, timeout=30)  # type: ignore


class TestObserverInterface:
    """
    A class for interfacing with the Test Observer API, in order to
    retrieve or remove rerun requests.
    """

    def __init__(
        self,
        family: Optional[str] = None,
        limit: Optional[int] = None
    ):
        # at the moment there is a single Test Observer deployment but
        # the rerun endpoint could be a constructor argument in the future
        self.reruns_endpoint = (
            "https://test-observer-api.canonical.com/v1/"
            "test-executions/reruns"
        )
        self.family = family
        self.limit = limit

    def create_get_params(self) -> Dict:
        """
        Return the query parameters for the GET request that
        retrieves the rerun requests from Test Observer
        """
        params = {"family": self.family, "limit": self.limit}
        return {
            parameter: value
            for parameter, value in params.items()
            if value is not None
        }

    def get(self) -> List[dict]:
        """
        Return the rerun requests currently queued in Test Observer.

        Raises an HTTPError if the operation fails.
        """
        response = requests.get(
            self.reruns_endpoint, params=self.create_get_params()
        )
        response.raise_for_status()
        return response.json()

    def delete(self, test_execution_ids: List[int]) -> None:
        """
        Remove a collection of rerun requests from Test Observer,
        as specified by their test execution IDs.

        Raises an HTTPError if the operation fails.
        """
        response = requests.delete(
            self.reruns_endpoint,
            json={"test_execution_ids": test_execution_ids}
        )
        response.raise_for_status()


class RequestProccesingError(ValueError):
    """
    Raised when a rerun request cannot be processed by a RequestProcessor
    """


class PostArguments(NamedTuple):
    """
    The POST arguments that would trigger a rerun.

    This is what the `RequestProcessor` class (below) produces
    when it processes a rerun request.
    """
    url: str
    json: Optional[Dict] = None


class RequestProcessor(ABC):
    """
    An abstract class for processing Test Observer rerun requests and
    triggering the corresponding reruns.
    """

    def __init__(self, constant_post_arguments: Dict):
        # these arguments will be part of any POST that triggers a rerun
        # (suitable e.g. for authorization)
        self.constant_post_arguments = constant_post_arguments

    @abstractmethod
    def process(self, rerun_request: dict) -> PostArguments:
        """
        Return a dict containing POST arguments that will trigger a rerun,
        based on a Test Observer rerun request.

        Raises an RequestProccesingError if the rerun request
        cannot be processed.
        """
        raise NotImplementedError

    def submit(self, post_arguments: PostArguments) -> None:
        """
        Combine all available arguments for triggering a rerun and submit them.

        Raises an HTTPError if the operation fails.
        """
        post_arguments_dict = {
            field: value
            for field, value in post_arguments._asdict().items()
            if value is not None
        }
        logging.info("POST %s", post_arguments_dict)
        response = requests.post(
            **{**self.constant_post_arguments, **post_arguments_dict}
        )
        response.raise_for_status()


class JenkinsProcessor(RequestProcessor):
    """
    Process Test Observer rerun requests for Jenkins jobs
    """

    # where Jenkins is deployed
    netloc = "10.102.156.15:8080"
    # what the path of Jenkins job run looks like
    path_template = r"job/(?P<job_name>[\w+-]+)/\d+"

    def __init__(self, user: str, password: str):
        auth = HTTPBasicAuth(user, password)
        super().__init__({"auth": auth})

    def process(self, rerun_request: dict) -> PostArguments:
        try:
            ci_link = rerun_request["ci_link"]
        except KeyError as error:
            raise RequestProccesingError(
                f"{type(self).__name__} cannot find ci_link "
                f"in rerun request {rerun_request}"
            ) from error
        if not ci_link:
            raise RequestProccesingError(
                f"{type(self).__name__} empty ci_link "
                f"in rerun request {rerun_request}"
            )
        # extract the rerun URL from the ci_link
        url = self.extract_rerun_url_from_ci_link(ci_link)
        # determine additional payload arguments
        # based on the artifact family in the rerun request
        try:
            family = rerun_request["family"]
        except KeyError as error:
            raise RequestProccesingError(
                f"{type(self).__name__} cannot find family "
                f"in rerun request {rerun_request}"
            ) from error
        if family == "deb":
            json = {
                "TEST_OBSERVER_REPORTING": True,
                "TESTPLAN": "full"
            }
        elif family == "snap":
            json = {
                "TEST_OBSERVER_REPORTING": True,
            }
        else:
            raise RequestProccesingError(
                f"{type(self).__name__} cannot process family '{family}' "
                f"in rerun request {rerun_request}"
            )
        return PostArguments(url=url, json=json)

    @classmethod
    def extract_rerun_url_from_ci_link(cls, ci_link: str) -> str:
        """
        Return the rerun URL for a Jenkins job, as determined by
        the ci_link in a rerun request.

        Raises a RerunRequestProccesingError if it's not possible to do so.
        """
        url_components = urlparse(ci_link)
        path = url_components.path.strip("/")
        match = re.match(cls.path_template, path)
        if url_components.netloc != cls.netloc or not match:
            raise RequestProccesingError(
                f"{cls.__name__} cannot process ci_link {ci_link}"
            )
        return (
            f"{url_components.scheme}://{url_components.netloc}/"
            f"job/{match.group('job_name')}/buildWithParameters"
        )


class GithubProcessor(RequestProcessor):
    """
    Process Test Observer rerun requests for Github workflows

    Ref: https://docs.github.com/en/rest/actions/workflow-runs
    """

    # where Github is
    netloc = "github.com"
    # what the path of Gitgub workflow run looks like
    path_template = r"canonical/(?P<repo>[\w-]+)/actions/runs/(?P<run_id>\d+)/job/\d+"

    def __init__(self, api_token: str, repo: Optional[str] = None):
        super().__init__(
            {
                "headers": {
                    "Accept": "application/vnd.github+json",
                    "Authorization": f"Bearer {api_token}"
                }
            }
        )
        self.repo = repo

    def process(self, rerun_request: dict) -> PostArguments:
        try:
            ci_link = rerun_request["ci_link"]
        except KeyError as error:
            raise RequestProccesingError(
                f"{type(self).__name__} cannot find ci_link "
                f"in rerun request {rerun_request}"
            ) from error
        if not ci_link:
            raise RequestProccesingError(
                f"{type(self).__name__} empty ci_link "
                f"in rerun request {rerun_request}"
            )
        url = self.extract_rerun_url_from_ci_link(ci_link)
        return PostArguments(url=url)

    def extract_rerun_url_from_ci_link(self, ci_link: str) -> str:
        """
        Return the rerun URL for a Github workflow, as determined by
        the ci_link in a rerun request.

        Raises a RerunRequestProccesingError if it's not possible to do so.
        """
        url_components = urlparse(ci_link)
        path = url_components.path.strip("/")
        match = re.match(self.path_template, path)
        if url_components.netloc != self.netloc or not match:
            raise RequestProccesingError(
                f"{type(self).__name__} cannot process ci_link {ci_link}"
            )
        repo = match.group('repo')
        if self.repo and self.repo != repo:
            raise RequestProccesingError(
                f"{type(self).__name__} repository in ci_link {ci_link}"
                f"doesn't match {self.repo}"
            )
        return (
            f"https://api.github.com/repos/"
            f"canonical/{repo}/"
            f"actions/runs/{match.group('run_id')}/rerun"
        )


# the Rerunner class (below) maps TestObserver execution IDs to
# the POST arguments that would trigger the corresponding rerun
ProcessedRequests = Dict[int, PostArguments]


class Rerunner:
    """
    Collect rerun requests from Test Observer and trigger the
    corresponding reruns.
    """

    def __init__(
        self, interface: TestObserverInterface, processor: RequestProcessor
    ):
        self.test_observer = interface
        self.processor = processor

    def load_rerun_requests(self) -> List[Dict]:
        """
        Return rerun requests retrieved from Test Observer
        """
        rerun_requests = self.test_observer.get()
        logging.info(
            "Received the following rerun requests:\n%s",
            str(rerun_requests)
        )
        return rerun_requests

    def process_rerun_requests(self, rerun_requests: List[Dict]) -> ProcessedRequests:
        """
        Process a list of rerun requests, selecting the ones that the
        processor can handle.

        Return a dict that maps execution IDs to the arguments required
        to trigger the corresponding rerun.
        """
        processed_requests: ProcessedRequests = {}
        for rerun_request in rerun_requests:
            try:
                post_arguments = self.processor.process(rerun_request)
            except RequestProccesingError:
                logging.warning(
                    "%s is unable to process this rerun request:\n%s",
                    type(self.processor).__name__,
                    str(rerun_request)
                )
            else:
                execution_id = rerun_request["test_execution_id"]
                processed_requests[execution_id] = post_arguments
        return processed_requests

    def submit_processed_requests(self, processed_requests: ProcessedRequests) -> List[int]:
        """
        Use the data generated by `process_rerun_requests` to trigger reruns.
        Return a list of Test Observer execution IDs corresponding to the
        reruns that were successfully triggered.
        """
        execution_ids_submitted_requests = []
        for execution_id, post_arguments in processed_requests.items():
            try:
                self.processor.submit(post_arguments)
            except HTTPError as error:
                # unable to POST: log the error
                logging.error(
                    "Response %s posting %s to %s",
                    error,
                    str(post_arguments),
                    type(self.processor).__name__
                )
            else:
                # mark this request as successfully serviced
                # (so that it can be removed from Test Observer's queue)
                execution_ids_submitted_requests.append(execution_id)
        return execution_ids_submitted_requests

    def delete_rerun_requests(self, execution_ids: List[int]) -> None:
        """
        Remove a list of rerun requests from Test Observer (as specified by
        their execution IDs).
        """
        if not execution_ids:
            return
        # sort the execution ids so that they are easier to locate in the log
        self.test_observer.delete((deleted := sorted(execution_ids)))
        logging.info(
            "Deleted rerun requests with execution ids: %s",
            ", ".join(map(str, deleted))
        )

    def run(self):
        """
        Collect, service and remove rerun requests
        """
        rerun_requests = self.load_rerun_requests()
        processed_requests = self.process_rerun_requests(rerun_requests)
        submitted_requests = self.submit_processed_requests(processed_requests)
        self.delete_rerun_requests(submitted_requests)


def create_rerunner_from_args():
    parser = ArgumentParser(
        description="Process Test Observer rerun requests"
    )
    parser.add_argument(
        "processor", choices=["jenkins", "github"],
        nargs="?", default="jenkins",
        help="Specify which request rerun processor to use"
    )
    parser.add_argument(
        "--family", help="Restrict processing to a specific family of artifacts"
    )
    parser.add_argument(
        "--limit", help="Restrict processing to a specific number of rerun requests"
    )
    # only for Github processor but too simple to justify using subparsers
    parser.add_argument(
        "--repo", help="Name of Github repository"
    )
    args = parser.parse_args()

    if args.processor == "jenkins":
        processor = JenkinsProcessor(
            environ.get("JENKINS_USERNAME") or "admin",
            environ["JENKINS_API_TOKEN"]
        )
    else:
        processor = GithubProcessor(environ["GH_TOKEN"], repo=args.repo)

    return Rerunner(
        interface=TestObserverInterface(
            family=args.family, limit=args.limit
        ),
        processor=processor
    )


if __name__ == "__main__":
    rerunner = create_rerunner_from_args()
    rerunner.run()
