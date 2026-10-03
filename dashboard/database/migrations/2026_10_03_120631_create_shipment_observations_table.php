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
        Schema::create('shipment_observations', function (Blueprint $table): void {
            $table->id();
            $table->foreignId('shipment_id')->constrained()->cascadeOnDelete();
            $table->timestamp('observed_at');
            $table->string('segment');
            $table->decimal('route_progress', 4, 3);
            $table->boolean('refrigerated');
            $table->decimal('product_temp_c', 5, 2);
            $table->decimal('ambient_c', 5, 2)->nullable();
            $table->decimal('river_level_cm', 6, 1)->nullable();
            $table->decimal('excursion_min', 8, 2)->default(0);
            $table->decimal('budget_used', 6, 3)->default(0);

            $table->index(['shipment_id', 'observed_at']);
        });
    }

    /**
     * Reverse the migrations.
     */
    public function down(): void
    {
        Schema::dropIfExists('shipment_observations');
    }
};
