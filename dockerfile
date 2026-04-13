FROM sql-driver17-pyodbc4.0.34-streamlit1.36.0-mlflow2.4.1-git-binary-copied-from-wsl:v1.0

RUN pip install dotenv==0.9.9 -i http://nexus.mehes.gov.il:8081/repository/python-hosted-repo/simple --trusted-host nexus.mehes.gov.il

RUN pip install mlflowfunctions -i https://pres57jrs4l7ddtg2fwjk7sts44bvg7h5qus4yfaoiblh3kk2jma@xtfs.head.ad.mehes.gov.il/DefaultCollection/general/_packaging/pypi_package/pypi/simple/ --trusted-host xtfs.head.ad.mehes.gov.il

WORKDIR /app

COPY main.py .

CMD ["python", "/app/main.py"]