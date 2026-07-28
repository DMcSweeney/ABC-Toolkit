FROM orthancteam/orthanc:26.6.1

# The Python plugin runs against the image's system Python, which doesn't bundle third-party
# packages by default - installed here so trigger.py can use `requests` like the rest of the
# backend's HTTP client code, instead of bare urllib.
RUN pip install --break-system-packages requests
