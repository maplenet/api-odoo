sudo apt install python3 python3-pip python3-venv


sudo mkdir -p /opt/fastapi/api
sudo chown -R test /opt/fastapi/
sudo chgrp -R test /opt/fastapi/
git clone https://github.com/maplenet/api-odoo.git --depth=1 /opt/fastapi/api
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
pip install uvicorn gunicorn

sudo nano /etc/systemd/system/api.service

[Unit]
Description=Integration API ODOO
After=network.target

[Service]
User=test
WorkingDirectory=/opt/fastapi/api
ExecStart=/bin/bash -c 'source /opt/fastapi/api/venv/bin/activate && /opt/fastapi/api/venv/bin/gunicorn -w 4 -k uvicorn.workers.UvicornWorker -b 0.0.0.0:8000 app.main:app'
Restart=always

[Install]
WantedBy=multi-user.target

deactivate

sudo systemctl daemon-reload
sudo systemctl start api.service
sudo systemctl enable api.service




sudo apt install nginx
server {
    listen 80;
    server_name yourdomain.com;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}

sudo ln -s /etc/nginx/sites-available/fastapi /etc/nginx/sites-enabled/
sudo systemctl restart nginx

sudo apt install certbot python3-certbot-nginx
sudo certbot --nginx -d yourdomain.com

sudo systemctl status fastapi.service