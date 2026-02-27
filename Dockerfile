FROM python:3-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN playwright install --with-deps chromium
COPY *.py /app/
COPY budget-email.html /app/
ENTRYPOINT ["python", "send_budget_reminder.py"]