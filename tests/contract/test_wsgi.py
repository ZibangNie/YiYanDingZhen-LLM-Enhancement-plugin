from yiyan_dingzhen.wsgi import create_application


def test_installed_wsgi_factory_is_available() -> None:
    app = create_application()

    assert app.name == "yiyan_dingzhen.app"
    assert app.test_client().get("/").data == b"welcomeb7!!!!!!"
