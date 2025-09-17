#########
#
# Create a running conquest 1.5.0d with web access and bash in Docker. 
# Note that this container DOES NOT RETAIN DATA after restart, 
# needs to be configured differently to achieve this.
#
# to build:
#    docker build -t ctest .
#
# to run the container interactively with bash:
#    docker run -it -p 8082:80 ctest conquest
#
# The container then offers these webpages:
# http://localhost:8082/app/ohif
# http://localhost:8082/app/luiz
# http://localhost:8082/app/newweb
#
##########


FROM debian

#get tools and libraries needed
RUN apt-get update
RUN apt-get -y install make sudo nano systemctl gettext-base git apache2 php libapache2-mod-php git g++ gcc lua5.1 liblua5.1-0 lua-socket p7zip-full curl
RUN ln -s /usr/lib/x86_64-linux-gnu/liblua5.1.so.0 /usr/lib/x86_64-linux-gnu/liblua5.1.so
#RUN ln -s /usr/lib/aarch64-linux-gnu/liblua5.1.so.0 /usr/lib/aarch64-linux-gnu/liblua5.1.so

#configure apache and restart it
RUN a2enmod rewrite
RUN sed -i 's/AllowOverride None/AllowOverride All/g' /etc/apache2/apache2.conf
RUN sed -i 's/memory_limit = 128M/memory_limit = 512M/g' /etc/php/*/apache2/php.ini
RUN sed -i 's/upload_max_filesize = 2M/upload_max_filesize = 250M/g' /etc/php/*/apache2/php.ini
RUN sed -i 's/post_max_size = 8M/post_max_size = 250M/g' /etc/php/*/apache2/php.ini
RUN systemctl restart apache2

# Make a workdir, to keep organised
#get conquest source code
RUN git clone https://github.com/marcelvanherk/Conquest-DICOM-Server

#COPY Conquest-DICOM-Server Conquest-DICOM-Server
WORKDIR /Conquest-DICOM-Server
RUN ls -l ./linux
#mark scripts as executable
RUN chmod 777 maklinux linux/regen linux/updatelinux linux/restart linux/updatelinux-docker

#compile, update dicom.ini if next to Dockerfile, and regenerate the SQLite database
RUN linux/updatelinux-docker
RUN linux/regen

## Update dicom.ini and add trigger.lua
COPY dicom.ini .
COPY trigger.lua ./lua/trigger.lua
COPY acrnema.map .

#finalise the web server
RUN chown -R www-data /var/www/html
RUN chmod 777 /var/www/html/api/dicom/servertask

#make the startup script executable
RUN cp ./linux/restart /usr/bin/conquest

## Add CMD to launch on startup
CMD ["conquest"]

###### additional docker commands:
#
#  to cleanup docker:
#  docker system prune -a
#
######