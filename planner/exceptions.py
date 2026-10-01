class PlannerError(Exception):
    """Base class. `status` is the HTTP status the API should answer with."""
    status = 400

    def __init__(self, message: str, status: int | None = None):
        super().__init__(message)
        if status is not None:
            self.status = status


class LocationError(PlannerError):
    status = 400


class RoutingError(PlannerError):
    status = 502


class NoRouteError(PlannerError):
    status = 422


class InfeasibleTripError(PlannerError):
    """No sequence of fuel stops can cover the route with the given range."""
    status = 422
