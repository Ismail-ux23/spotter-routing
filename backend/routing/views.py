import json
import logging
import requests
from django.core.exceptions import RequestDataTooBig
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from .service import plan, ProviderRateLimit, ProviderError

logger = logging.getLogger(__name__)


def health(request):
    return JsonResponse({"status": "ok"})


@csrf_exempt
def routes(request):
    # Stateless endpoint: no cookies, authentication or persisted mutations.
    if request.method != "POST":
        response = JsonResponse({"error": "POST required"}, status=405)
        response["Allow"] = "POST"
        return response
    if request.content_type != "application/json":
        return JsonResponse({"error": "Send application/json."}, status=415)
    try:
        payload = json.loads(request.body)
        if not isinstance(payload, dict):
            raise ValueError("Expected a JSON object.")
        return JsonResponse(plan(payload))
    except RequestDataTooBig:
        return JsonResponse({"error": "Request is too large."}, status=413)
    except (ValueError, KeyError, TypeError, OverflowError) as error:
        return JsonResponse({"error": str(error)}, status=400)
    except ProviderRateLimit as error:
        response = JsonResponse(
            {"error": str(error), "retry_after": error.retry_after}, status=429
        )
        response["Retry-After"] = str(error.retry_after)
        return response
    except ProviderError as error:
        return JsonResponse({"error": str(error)}, status=502)
    except requests.RequestException:
        return JsonResponse(
            {
                "error": "Routing or weather provider is unavailable or rate-limited. Please retry shortly."
            },
            status=502,
        )
    except Exception:
        logger.exception("Route planning failed")
        return JsonResponse(
            {
                "error": "Unable to complete this trip. Please retry or choose another destination."
            },
            status=500,
        )
