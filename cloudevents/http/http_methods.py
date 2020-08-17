import json
import typing

from deprecation import deprecated

import cloudevents.exceptions as cloud_exceptions
from cloudevents.http.event import CloudEvent
from cloudevents.http.event_type import is_binary, is_structured
from cloudevents.http.mappings import _marshaller_by_format, _obj_by_version
from cloudevents.http.util import _json_or_string
from cloudevents.sdk import converters, marshaller, types


def from_http(
    headers: typing.Dict[str, str],
    data: typing.Union[str, bytes, None],
    data_unmarshaller: types.UnmarshallerType = None,
):
    """
    Unwrap a CloudEvent (binary or structured) from an HTTP request.
    :param headers: the HTTP headers
    :type headers: typing.Dict[str, str]
    :param data: the HTTP request body
    :type data: typing.IO
    :param data_unmarshaller: Callable function to map data to a python object
        e.g. lambda x: x or lambda x: json.loads(x)
    :type data_unmarshaller: types.UnmarshallerType
    """
    if data is None:
        data = ""

    if not isinstance(data, (str, bytes, bytearray)):
        raise cloud_exceptions.InvalidStructuredJSON(
            "Expected json of type (str, bytes, bytearray), "
            f"but instead found {type(data)}. "
        )

    headers = {key.lower(): value for key, value in headers.items()}
    if data_unmarshaller is None:
        data_unmarshaller = _json_or_string

    marshall = marshaller.NewDefaultHTTPMarshaller()

    if is_binary(headers):
        specversion = headers.get("ce-specversion", None)
    else:
        try:
            raw_ce = json.loads(data)
        except json.decoder.JSONDecodeError:
            raise cloud_exceptions.InvalidStructuredJSON(
                "Failed to read fields from structured event. "
                f"The following can not be parsed as json: {data}. "
            )
        specversion = raw_ce.get("specversion", None)

    if specversion is None:
        raise cloud_exceptions.CloudEventMissingRequiredFields(
            "Specversion was set to None in HTTP request. "
        )

    event_handler = _obj_by_version.get(specversion, None)

    if event_handler is None:
        raise cloud_exceptions.CloudEventTypeErrorRequiredFields(
            f"Found invalid specversion {specversion}. "
        )

    event = marshall.FromRequest(
        event_handler(), headers, data, data_unmarshaller=data_unmarshaller
    )
    attrs = event.Properties()
    attrs.pop("data", None)
    attrs.pop("extensions", None)
    attrs.update(**event.extensions)

    return CloudEvent(attrs, event.data)


def _to_http(
    event: CloudEvent,
    format: str = converters.TypeStructured,
    data_marshaller: types.MarshallerType = None,
) -> (dict, typing.Union[bytes, str]):
    """
    Returns a tuple of HTTP headers/body dicts representing this cloudevent

    :param format: constant specifying an encoding format
    :type format: str
    :param data_marshaller: Callable function to cast event.data into
        either a string or bytes
    :type data_marshaller: types.MarshallerType
    :returns: (http_headers: dict, http_body: bytes or str)
    """
    if data_marshaller is None:
        data_marshaller = _marshaller_by_format[format]

    if event._attributes["specversion"] not in _obj_by_version:
        raise cloud_exceptions.CloudEventTypeErrorRequiredFields(
            f"Unsupported specversion: {event._attributes['specversion']}. "
        )

    event_handler = _obj_by_version[event._attributes["specversion"]]()
    for k, v in event._attributes.items():
        event_handler.Set(k, v)
    event_handler.data = event.data

    return marshaller.NewDefaultHTTPMarshaller().ToRequest(
        event_handler, format, data_marshaller=data_marshaller
    )


def to_structured(
    event: CloudEvent, data_marshaller: types.MarshallerType = None,
) -> (dict, typing.Union[bytes, str]):
    """
    Returns a tuple of HTTP headers/body dicts representing this cloudevent

    :param event: CloudEvent to cast into http data
    :type event: CloudEvent
    :param data_marshaller: Callable function to cast event.data into
        either a string or bytes
    :type data_marshaller: types.MarshallerType
    :returns: (http_headers: dict, http_body: bytes or str)
    """
    return _to_http(event=event, data_marshaller=data_marshaller)


def to_binary(
    event: CloudEvent, data_marshaller: types.MarshallerType = None,
) -> (dict, typing.Union[bytes, str]):
    """
    Returns a tuple of HTTP headers/body dicts representing this cloudevent

    :param event: CloudEvent to cast into http data
    :type event: CloudEvent
    :param data_marshaller: Callable function to cast event.data into
        either a string or bytes
    :type data_marshaller: types.UnmarshallerType
    :returns: (http_headers: dict, http_body: bytes or str)
    """
    return _to_http(
        event=event,
        format=converters.TypeBinary,
        data_marshaller=data_marshaller,
    )


@deprecated(deprecated_in="1.0.2", details="Use to_binary function instead")
def to_binary_http(
    event: CloudEvent, data_marshaller: types.MarshallerType = None,
) -> (dict, typing.Union[bytes, str]):
    return to_binary(event, data_marshaller)


@deprecated(deprecated_in="1.0.2", details="Use to_structured function instead")
def to_structured_http(
    event: CloudEvent, data_marshaller: types.MarshallerType = None,
) -> (dict, typing.Union[bytes, str]):
    return to_structured(event, data_marshaller)
