import logging
import json
import zlib
import base64
from uuid import uuid4
from io import BytesIO


logger = logging.getLogger(__name__)


def store_jsondata(objstore, bucket_name, object_name, jsondata, metadata={}):
    logger.info(f"LOOKIE HERE: Storing jsondata in object store: {bucket_name}:{object_name} (metadata: {metadata})")
    objstore.put_object(
        bucket_name,
        object_name,
        BytesIO(json.dumps(jsondata).encode()),
        -1,
        "application/json",
        metadata=metadata,
        part_size=50*1024*1024
    )


def store_b64comp_jsondata(objstore, bucket_name, object_name, jsondata, metadata={}):
    logger.info(f"Storing b64(comp(jsondata)) in object store: {bucket_name}:{object_name} (metadata: {metadata})")
    b64decomp = zlib.decompress(base64.b64decode(jsondata))
    objstore.put_object(
        bucket_name,
        object_name,
        BytesIO(b64decomp),
        -1,
        "application/json",
        metadata=metadata,
        part_size=50*1024*1024
    )


def store_b64comp_pngdata(objstore, bucket_name, object_name, pngdata, metadata={}):
    logger.info(f"Storing b64(comp(png)) in object store: {bucket_name}:{object_name} (metadata: {metadata})")
    b64decomp = zlib.decompress(base64.b64decode(pngdata))
    objstore.put_object(
        bucket_name,
        object_name,
        BytesIO(b64decomp),
        -1,
        "image/png",
        metadata=metadata,
        part_size=50*1024*1024
    )


def store_and_mutate_data(objstore, bucket_name, prefix, data, ext):
    """ stores data in object store and mutates to reference
        input data: any json serializable data
        output data: {"type": "reference", "data": {"bucket_name": "<bucket_name>", "object_name": "/<prefix>/<uuid>.<ext>", "extension": "<ext>"}}
    """
    logger.info(f"Storing data to database{objstore, bucket_name, prefix, data}")
    print(f"Storing data to database{objstore, bucket_name, prefix, data}")
    uuid = uuid4()
    object_name = f"/{prefix}/{uuid}.{ext}"
    logger.info(f"Storing and mutating data of type {ext}: {bucket_name}:{object_name}")
    if data is None:
        logger.info(f"Do not store data with none value")
        return data
    elif ext == "png":
        store_b64comp_pngdata(objstore, bucket_name, object_name, data)
        return {"type": "reference", "data": {"bucket_name": bucket_name, "object_name": object_name, "extension": ext}}
    elif ext == "har":
        store_b64comp_jsondata(objstore, bucket_name, object_name, data)
        return {"type": "reference", "data": {"bucket_name": bucket_name, "object_name": object_name, "extension": ext}}
    elif ext == "json":
        store_jsondata(objstore, bucket_name, object_name, data)
        return {"type": "reference", "data": {"bucket_name": bucket_name, "object_name": object_name, "extension": ext}}
    else:
        logger.error(f"Failed to store data with unknown extension: {ext}")
        return data
