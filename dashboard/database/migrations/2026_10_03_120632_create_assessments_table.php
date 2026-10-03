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
        Schema::create('assessments', function (Blueprint $table): void {
            $table->id();
            $table->foreignId('shipment_id')->constrained()->cascadeOnDelete();
            $table->timestamp('assessed_at');
            $table->string('model');
            $table->decimal('p_miss_slot', 5, 4);
            $table->decimal('p_excursion', 5, 4);
            $table->decimal('budget_used', 6, 3);
            $table->timestamp('eta_p50')->nullable();
            $table->timestamp('eta_p90')->nullable();
            $table->string('recommended_action');
            $table->string('approver_role');
            $table->json('answers');
            $table->json('options');
            $table->json('reasons');
            $table->json('would_change_if');
            $table->json('signals')->nullable();
            $table->json('briefing')->nullable();
            $table->char('snapshot_sha256', 64);
            $table->timestamps();

            $table->index(['shipment_id', 'assessed_at']);
        });
    }

    /**
     * Reverse the migrations.
     */
    public function down(): void
    {
        Schema::dropIfExists('assessments');
    }
};
