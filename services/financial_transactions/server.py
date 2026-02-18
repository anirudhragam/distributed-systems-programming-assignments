import random
from wsgiref.simple_server import make_server

from spyne import Application, Integer, ServiceBase, Unicode, rpc
from spyne.protocol.soap import Soap11
from spyne.server.wsgi import WsgiApplication


class FinancialTransactionsService(ServiceBase):

    @rpc(Unicode, Unicode, Integer, Integer, Unicode, _returns = Unicode)
    def process_payment(ctx, cardholder_name, card_number, expiry_month, expiry_year, security_code):
        return "Yes" if random.random() < 0.9 else "No"

application = Application(
    [FinancialTransactionsService],
    tns = "financial.transactions",
    in_protocol = Soap11(validator="lxml"),
    out_protocol = Soap11()
)

if __name__ == "__main__":
    wsgi_app = WsgiApplication(application)
    server = make_server("0.0.0.0", 8000, wsgi_app)
    # serves WSDL at http://financial-transactions:8000/?wsdl
    server.serve_forever()