from app.profile import Profile, get_profile


def test_example_profile_validates():
    get_profile.cache_clear()
    profile = get_profile()

    assert isinstance(profile, Profile)
    assert profile.personal.name
    assert profile.education
    assert profile.standard_answers.work_authorization
