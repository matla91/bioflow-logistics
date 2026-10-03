<?php

declare(strict_types=1);

namespace Database\Seeders;

use App\Enums\UserRole;
use App\Models\User;
use Illuminate\Database\Seeder;

final class DemoUserSeeder extends Seeder
{
    /**
     * One demo login per role, all with the password "secret".
     */
    public function run(): void
    {
        $users = [
            ['email' => 'operator@example.com', 'name' => 'Night Operator', 'role' => UserRole::Operator],
            ['email' => 'logistics@example.com', 'name' => 'Logistics Lead', 'role' => UserRole::Logistics],
            ['email' => 'qa@example.com', 'name' => 'QA Reviewer', 'role' => UserRole::Qa],
        ];

        foreach ($users as $user) {
            User::query()->updateOrCreate(['email' => $user['email']], [
                'name' => $user['name'],
                'role' => $user['role'],
                'password' => 'secret',
                'email_verified_at' => now(),
            ]);
        }
    }
}
