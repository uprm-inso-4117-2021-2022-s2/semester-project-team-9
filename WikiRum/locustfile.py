import json
from locust import HttpUser, task, between


class MyUser(HttpUser):
    wait_time = between(1, 5)
    @task
    def hello_world(self):
        self.client.get("")

    @task
    def signUp(self):
        url = 'signup'
        data = {
            'username': 'john',
            'email': 'john@doe.com',
            'password1': 'abcdef123456',
            'password2': 'abcdef123456',
        }
        self.client.post(url, data)

    @task
    def postpage(self):
        url ='pages/newpage'
        data = {
            'title':'Bioligy',
            'text':'This is the bioligy page',
            'category':'Department',
        }
        self.client.post(url, data)
