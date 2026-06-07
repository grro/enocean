FROM python:3-alpine

ENV port 8343
ENV directory ""
ENV path "?"
ENV devices "?"
ENV mcp_port 8345
ENV mcp_host 0.0.0.0
ENV mcp_name WindowHandles

RUN cd /etc
RUN mkdir app
WORKDIR /etc/app
ADD *.py /etc/app/
ADD requirements.txt /etc/app/.
RUN pip install -r requirements.txt

CMD python /etc/app/run_server.py $directory $port $path $devices --mcp-host $mcp_host --mcp-name $mcp_name --mcp-port $mcp_port



