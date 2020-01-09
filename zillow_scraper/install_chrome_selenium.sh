# Install Chrome.
sudo curl -sS -o - https://dl-ssl.google.com/linux/linux_signing_key.pub | sudo apt-key add -
#sudo echo "deb http://dl.google.com/linux/chrome/deb/ stable main" >> /etc/apt/sources.list.d/google-chrome.list
echo "deb http://dl.google.com/linux/chrome/deb/ stable main" >> ./google-chrome.list
sudo cp ./google-chrome.list /etc/apt/sources.list.d/
sudo apt-get -y update
sudo apt-get -y install google-chrome-stable

# Install ChromeDriver for Selenium
sudo apt-get -y install unzip
# Old version for chrome between 70 and 73
#wget -N http://chromedriver.storage.googleapis.com/2.45/chromedriver_linux64.zip -P ~/
# New version for chrome 77
wget -N https://chromedriver.storage.googleapis.com/79.0.3945.36/chromedriver_linux64.zip -P ~/
unzip ~/chromedriver_linux64.zip -d ~/
rm ~/chromedriver_linux64.zip
sudo mv -f ~/chromedriver /usr/local/bin/chromedriver
sudo chown root:root /usr/local/bin/chromedriver
sudo chmod 0755 /usr/local/bin/chromedriver


