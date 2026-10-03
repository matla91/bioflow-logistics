<?php

declare(strict_types=1);

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

return new class extends Migration
{
    /**
     * Run the migrations.
     */
    public function up(): void
    {
        Schema::create('shipments', function (Blueprint $table): void {
            $table->id();
            $table->string('lot')->unique();
            $table->string('external_ref')->nullable()->unique();
            $table->string('scenario')->nullable();
            $table->boolean('simulated')->default(true);
            $table->string('material');
            $table->string('origin');
            $table->string('reactor');
            $table->string('timezone')->default('Europe/Zurich');
            $table->timestamp('departed_at');
            $table->timestamp('charge_at');
            $table->timestamp('eta')->nullable();
            $table->timestamp('arrived_at')->nullable();
            $table->string('status');
            $table->string('current_segment');
            $table->decimal('route_progress', 4, 3)->default(0);
            $table->timestamps();

            $table->index(['status', 'charge_at']);
        });
    }

    /**
     * Reverse the migrations.
     */
    public function down(): void
    {
        Schema::dropIfExists('shipments');
    }
};
