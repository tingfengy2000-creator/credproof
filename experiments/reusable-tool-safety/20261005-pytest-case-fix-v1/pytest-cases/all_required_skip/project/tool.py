def run(request):
    return {'ok': True, 'resource': request.get('resource')}
