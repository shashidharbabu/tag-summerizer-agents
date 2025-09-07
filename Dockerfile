FROM nginx:alpine

COPY . /usr/share/nginx/html

#port
EXPOSE 80
