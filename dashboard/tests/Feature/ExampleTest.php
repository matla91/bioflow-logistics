<?php

use App\Models\User;

test('root redirects guests to the login page', function () {
    $this->get(route('home'))->assertRedirect('/login');
});

test('root sends authenticated users to the dashboard', function () {
    $this->actingAs(User::factory()->create())
        ->followingRedirects()
        ->get(route('home'))
        ->assertOk()
        ->assertInertia(fn ($page) => $page->component('Dashboard'));
});
