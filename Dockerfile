FROM public.ecr.aws/docker/library/python:3.13.1-alpine3.21 AS install
LABEL NAME="BlackDuck SCIM"
LABEL VERSION=0.0.1

WORKDIR /
RUN mkdir -m 777 -p scim
RUN python -m pip install --upgrade pip 
RUN pip install pipenv
COPY requirements.txt /scim/
RUN pip install -r /scim/requirements.txt
COPY scim_blackducksca.py /scim/
COPY scimUserSchema.json /scim/
COPY LICENSE /scim/
EXPOSE 8090/tcp
WORKDIR /scim
ENTRYPOINT ["python", "scim_blackducksca.py"]