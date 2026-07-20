FROM python:3.10

RUN apt-get update && apt-get upgrade -y
RUN apt-get install gcc ffmpeg libsm6 libxext6 xvfb unzip -y

# Mount the data directory
VOLUME [ "/data" ]

#Set working dir
WORKDIR /src

RUN python -m pip install -U pip

# Clone ABC-core
## RUN git clone https://github.com/DMcSweeney/abc-core.git abcCore

# Is this still needed?
RUN export PATH="/home/appuser/.local/bin:$PATH" 

# Copy app scripts and models
# COPY app/* .
# App folder is mounted from host for live updates
RUN wget --max-redirect=20 -O /tmp/models.zip "https://www.dropbox.com/scl/fo/5sw8m4zi1w8cevlryh6cf/AESO5S2bGkB0GmkAVAeeMrE?rlkey=vqh6k2m7msy4gycd2dck9wctt&st=575p9x1v&dl=1" \
 && unzip /tmp/models.zip -d /models -x '/' \
 && rm /tmp/models.zip
#COPY ./models /models
COPY ./src/ .

## Install requirements
COPY requirements.txt .
RUN python -m pip install -r requirements.txt

CMD [ "flask", "run"]
