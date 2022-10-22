Threads

* Trigger-ConfigMap

    * Sets trigger var

* Trigger-SQS

    * Sets trigger var

* Trigger-Webhook

    * Sets trigger var

* Scale-loop

    * Starts when trigger found
    * If ongoing, reconcile
    * If not ongoing, check for orphans (can be split of to separate thread, lower freq.)

* Process-orphans-loop

    * Searches for HPA




* https://superfastpython.com/extend-thread-class/
* https://superfastpython.com/interrupt-the-main-thread-in-python/
* https://www.geeksforgeeks.org/python-different-ways-to-kill-a-thread/
* https://blog.miguelgrinberg.com/post/how-to-kill-a-python-thread
