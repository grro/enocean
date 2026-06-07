# enocean
A web-connected enocean gateway. This project provides a [webthing API](https://iot.mozilla.org/wot/) for an enocean gateway like the [EnOcean USB 300 USB gateway](https://www.enocean.com/de/produkt/usb-300-500u-400j/).

The enocean_webthing package provides a http webthing endpoint that supports enocean devices.

E.g.
```
# webthing has been started on host 192.168.0.23

curl http://192.168.1.198:9090/0/properties

{
   "eep_id":"F6:10:00",
   "enocean_id":"81:00:F0:4E",
   "state":3
}
```
Currently, the following [devices](https://www.enocean-alliance.org/wp-content/uploads/2017/05/EnOcean_Equipment_Profiles_EEP_v2.6.7_public.pdf) are supported.
* Window handle like [HOPPE window handle ConnectHome](https://www.hoppe.com/in-en/window-handles/hoppe-innovations-window-handles/ehandle-connecthome-for-windows/) (EEP ID: F6:10:00).

