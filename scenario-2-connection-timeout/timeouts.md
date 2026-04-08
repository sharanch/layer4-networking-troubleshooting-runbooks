sudo tcpdump -i lo port 9999 -n - terminal 1 - read the packages
sudo iptables -A INPUT -p tcp --dport 9999 -j DROP -- iptable rules to drop incoming packages to 9999 port

telnet localhost 9999 - now this get stuck because the firewall is dropping connections and the tcpdump will show the reattempts of telnet 

sudo iptables -D INPUT -p tcp --dport 9999 -j DROP - to delete the rule
