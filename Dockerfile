FROM python:3.7

#update
RUN apt-get update

#copy app
COPY . /
WORKDIR /
RUN pip3 install -r requirements.txt

CMD ["gunicorn", "-w", "3", "-b", ":5000", "-t", "360", "--reload", "wsgi:app"]