FROM python:3-alpine

ENV port 8343
ENV directory ""
ENV path "?"
ENV devices "?"

RUN cd /etc
RUN mkdir app
WORKDIR /etc/app
ADD *.py /etc/app/
ADD requirements.txt /etc/app/.
RUN pip install -r requirements.txt

CMD python /etc/app/run_server.py $directory $port $path $devices



